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
TEST_PROVIDER2 = "test_zzz_regsync2"  # a second vendor for cross-block cases (BQ2)
TEST_PREFIX = "test_zzz"  # every provider a test may write starts with this (BQ2 guard)
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
            cur.execute(
                "DELETE FROM services WHERE provider IN (%s, %s)", (TEST_PROVIDER, TEST_PROVIDER2)
            )
        conn.close()
    except Exception:  # noqa: BLE001
        pass


def _real_rows():
    """Every NON-test provider's service + key rows, or None when the registry is unreachable."""
    try:
        conn = rdb.connect()
    except Exception:  # noqa: BLE001
        return None
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT s.provider, s.category, s.cost_tier, s.url, s.status, k.value_sha256, k.kind, "
            "k.used_by_projects FROM services s LEFT JOIN api_keys k ON k.service_id=s.id "
            "WHERE s.provider NOT LIKE %s ORDER BY 1, 6",
            (TEST_PREFIX + "%",),
        )
        rows = cur.fetchall()
    conn.close()
    return rows


@pytest.fixture
def syncs_the_real_registry(request):
    """Opt-out for the ONE kind of test that syncs the REAL all-envs.env on purpose (the prune
    guard's proof): the real rows legitimately move with the file; the guard below stands down."""
    request.node.syncs_the_real_registry = True


@pytest.fixture(autouse=True)
def real_registry_untouched(request):
    """A test leaves every real provider's rows byte-identical on the SHARED local registry:
    fixtures that named `deepl`/`exa` overwrote deepl's cost tier (freemium → paid) and left fake
    `projA` key rows that the dashboard then counted, invisible until a finder looked (BQ2)."""
    before = _real_rows()
    yield
    if before is not None and not getattr(request.node, "syncs_the_real_registry", False):
        after = _real_rows()
        assert after == before, (
            "a test wrote a REAL provider's rows — use TEST_PROVIDER/TEST_PROVIDER2"
        )


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


def test_prune_removes_orphans(syncs_the_real_registry):
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


def test_credit_fetcher_gets_the_credential_never_a_code_host_url(fixture_env, monkeypatch):
    """A code call-site line (`CODE_HOST_URL=https://…`) sorts BEFORE `DEEPL_API_KEY`; the credit
    fetcher must still receive the credential — a URL as api_key silently loses the daily balance
    snapshot (found by the 2026-09-02 review, N1)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " translation " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=translation cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"CODE_HOST_URL=https://api-free.deepl.com   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_API_KEY={SECRET}\n",
        encoding="utf-8",
    )
    got: list[tuple[str, str]] = []
    monkeypatch.setattr(rs, "fetch_balance", lambda name, value: got.append((name, value)) or None)
    rs.sync_registry(fetch_credits=True, prune=False)
    assert got == [(TEST_PROVIDER, SECRET)], got


def test_credential_chosen_by_key_role_not_line_order(fixture_env, monkeypatch):
    """AZURE_ACCOUNT_NAME sorts before AZURE_API_KEY and is credential-KIND by value entropy (a
    26-char alnum account name) but not by NAME: the anchored key feeds the fetcher whatever the
    line order (review O5; AM1 — AH2 had made the choice positional and this fixture vacuous)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " infra " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=infra cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_ACCOUNT_NAME=fabrikstorageaccount2026x1   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_API_KEY={SECRET}\n",
        encoding="utf-8",
    )
    got: list[tuple[str, str]] = []
    monkeypatch.setattr(rs, "fetch_balance", lambda name, value: got.append((name, value)) or None)
    rs.sync_registry(fetch_credits=True, prune=False)
    assert got == [(TEST_PROVIDER, SECRET)], got


def test_code_host_rows_are_kind_code_host_and_never_counted_as_keys(fixture_env):
    """A code-only provider shows 0 keys on the dashboard while its projects still attribute
    (review O4): the api_keys row exists with kind='code-host'."""
    fixture_env.write_text(
        "# " + "═" * 10 + " observability " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=observability cost=? capability="?" '
        "url=https://api.posthog.com status=? used_by=projA\n"
        "CODE_HOST_URL=https://api.posthog.com   # used by: projA\n",
        encoding="utf-8",
    )
    rs.sync_registry(fetch_credits=False, prune=False)
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT k.kind FROM api_keys k JOIN services s ON s.id=k.service_id WHERE s.provider=%s",
            (TEST_PROVIDER,),
        )
        kinds = [row[0] for row in cur.fetchall()]
    conn.close()
    assert kinds == ["code-host"]
    gd = _load("gen_dashboard")
    row = next(r for r in gd.load() if r["provider"] == TEST_PROVIDER)
    assert row["keys"] == 0 and "projA" in row["projects"]


def test_kind_is_the_synthetic_key_never_a_value_shape(fixture_env, monkeypatch):
    """A proxy URL with userinfo is a CREDENTIAL; only CODE_HOST_URL rows are code-host (G3);
    a numbered key name (GROQ_API_KEY_2) outranks the DSN for the fetcher even when the DSN's
    line sorts first (G4; the fixture order is the DISCRIMINATING one — AM2)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " proxies " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=proxies cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        "CODE_HOST_URL=https://api.x.example   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_A_PROXY_URL=http://user:{SECRET}@45.61.127.38:5977   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_API_KEY_2={SECRET}zz\n",
        encoding="utf-8",
    )
    got: list[tuple[str, str]] = []
    monkeypatch.setattr(rs, "fetch_balance", lambda name, value: got.append((name, value)) or None)
    rs.sync_registry(fetch_credits=True, prune=False)
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT k.kind, count(*) FROM api_keys k JOIN services s ON s.id=k.service_id "
            "WHERE s.provider=%s GROUP BY 1 ORDER BY 1",
            (TEST_PROVIDER,),
        )
        kinds = cur.fetchall()
    conn.close()
    assert kinds == [("code-host", 1), ("credential", 2)], (
        kinds
    )  # a proxy URL with a password IS a credential
    assert got == [(TEST_PROVIDER, f"{SECRET}zz")], got  # the anchored name outranks the DSN


def test_stale_key_rows_are_pruned_per_service(fixture_env):
    """A key that leaves a provider (a code host no longer referenced, a var reclassified as
    internal-config) must not survive as a phantom credential (closing review 2026-09-02, N2)."""
    rs.sync_registry(fetch_credits=False, prune=False)  # fixture: one key
    fixture_env.write_text(
        "# " + "═" * 10 + " ai-llm " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=ai-llm cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"CODE_HOST_URL=https://api.x.example   # used by: projA\n",
        encoding="utf-8",
    )
    stats = rs.sync_registry(fetch_credits=False, prune=False, prune_keys=True)
    assert stats["keys_pruned"] == 1
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT k.kind FROM api_keys k JOIN services s ON s.id=k.service_id WHERE s.provider=%s",
            (TEST_PROVIDER,),
        )
        kinds = [row[0] for row in cur.fetchall()]
    conn.close()
    assert kinds == ["code-host"], kinds


def test_ensure_schema_never_alters_when_the_column_exists():
    """An unconditional ALTER (even IF NOT EXISTS) takes ACCESS EXCLUSIVE and waits behind any
    open reader — the daily sync must not lock-fight the dashboard server (N3)."""

    class _Cur:
        def __init__(self, present: bool):
            self.present, self.sql = present, []

        def execute(self, q, *a):
            self.sql.append(q)

        def fetchone(self):
            return (1,) if self.present else None

    cur = _Cur(present=True)
    rs.ensure_schema(cur)
    assert len(cur.sql) == 1 and cur.sql[0].lstrip().upper().startswith("SELECT")
    cur = _Cur(present=False)
    rs.ensure_schema(cur)
    assert len(cur.sql) == 2 and "ALTER TABLE api_keys" in cur.sql[1]


def test_key_prune_skips_a_provider_with_no_values(fixture_env):
    """`value_sha256 <> ALL('{}')` is TRUE for every row: a block whose values are all empty must
    not wipe the provider's existing keys (pass 5, orchestrator)."""
    rs.sync_registry(fetch_credits=False, prune=False)  # fixture: one real key
    fixture_env.write_text(
        "# " + "═" * 10 + " ai-llm " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=ai-llm cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_API_KEY=\n",
        encoding="utf-8",
    )
    stats = rs.sync_registry(fetch_credits=False, prune=False, prune_keys=True)
    assert stats["keys_pruned"] == 0
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM api_keys k JOIN services s ON s.id=k.service_id WHERE s.provider=%s",
            (TEST_PROVIDER,),
        )
        n = cur.fetchone()[0]
    conn.close()
    assert n == 1


def test_partial_file_sync_keeps_a_providers_other_keys(fixture_env):
    """`prune=False` is the partial-file contract: a subset of a provider's keys must not delete
    the rest (pass 5, Z7)."""
    rs.sync_registry(fetch_credits=False, prune=False)  # one key
    fixture_env.write_text(
        "# " + "═" * 10 + " ai-llm " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=ai-llm cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_OTHER_TOKEN={SECRET}other\n",
        encoding="utf-8",
    )
    stats = rs.sync_registry(fetch_credits=False, prune=False)  # partial: keys untouched
    assert stats["keys_pruned"] == 0
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM api_keys k JOIN services s ON s.id=k.service_id WHERE s.provider=%s",
            (TEST_PROVIDER,),
        )
        n = cur.fetchone()[0]
    conn.close()
    assert n == 2


def test_config_knobs_under_a_vendor_are_kind_config_not_credential(fixture_env):
    """`IPROYAL_HOST=proxy.iproyal.com` is a config knob: kind='config', never counted as a key (AC6)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " proxies " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=proxies cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_HOST=proxy.example.com   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_API_URL=https://api.example.com/v2/very/long/path   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_DB_URL=postgresql://user:{SECRET}@db.example.com:5432/x   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_API_KEY={SECRET}\n",
        encoding="utf-8",
    )
    rs.sync_registry(fetch_credits=False, prune=False)
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT k.kind, count(*) FROM api_keys k JOIN services s ON s.id=k.service_id "
            "WHERE s.provider=%s GROUP BY 1 ORDER BY 1",
            (TEST_PROVIDER,),
        )
        kinds = cur.fetchall()
    conn.close()
    assert kinds == [("config", 2), ("credential", 2)], (
        kinds
    )  # URL = config; DSN with a password = credential (AF1)


def test_public_identifiers_are_config_not_credentials(fixture_env):
    """`M365_CLIENT_ID=<uuid>` is a public OAuth identifier: entropy alone must not make it a
    credential (AD1); the real key still is."""
    fixture_env.write_text(
        "# " + "═" * 10 + " infra " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=infra cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_CLIENT_ID=f1d296cb-b397-41d5-85cd-0a52c79bebe9   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_TENANT_ID=6d57bdf0-257f-4317-97d4-5daddff17baf   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_CLIENT_SECRET={SECRET}\n",
        encoding="utf-8",
    )
    rs.sync_registry(fetch_credits=False, prune=False)
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT k.kind, count(*) FROM api_keys k JOIN services s ON s.id=k.service_id "
            "WHERE s.provider=%s GROUP BY 1 ORDER BY 1",
            (TEST_PROVIDER,),
        )
        kinds = cur.fetchall()
    conn.close()
    assert kinds == [("config", 2), ("credential", 1)], kinds


def test_unanchored_secret_token_needs_a_secret_shaped_value(fixture_env, monkeypatch):
    """`X_IP_AUTH=false` carries `_AUTH` in its name but is a boolean knob → config (AH1); a
    provider whose ONLY credential is a userinfo DSN still feeds the fetcher (AH2)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " proxies " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=proxies cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_IP_AUTH=false   # used by: projA\n"
        f"{TEST_PROVIDER.upper()}_PROXY_URL=http://user:{SECRET}@45.61.127.38:5977   # used by: projA\n",
        encoding="utf-8",
    )
    got: list[tuple[str, str]] = []
    monkeypatch.setattr(rs, "fetch_balance", lambda name, value: got.append((name, value)) or None)
    rs.sync_registry(fetch_credits=True, prune=False)
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT k.kind, count(*) FROM api_keys k JOIN services s ON s.id=k.service_id "
            "WHERE s.provider=%s GROUP BY 1 ORDER BY 1",
            (TEST_PROVIDER,),
        )
        kinds = cur.fetchall()
    conn.close()
    assert kinds == [("config", 1), ("credential", 1)], kinds
    assert got == [(TEST_PROVIDER, f"http://user:{SECRET}@45.61.127.38:5977")], got


def test_identifier_survives_a_qualifier_and_a_locator_is_never_a_credential():
    """`CLOUDFLARE_ZONE_ID_OCORON` (identifier + tenant qualifier), `N8N_WEBHOOK_CONTENT` and
    `RESTIC_REPOSITORY` (locators), `M365_CERT_KEY_FILE=/…/x.pem` (a path) are config — the
    `_ID$` anchor let a qualifier escape it (AJ4); a qualifier that IS a secret token (`_HOST_AUTH`)
    never demotes, and `_ID_TOKEN` stays anchored-credential."""
    assert not rs.is_credential("CLOUDFLARE_ZONE_ID_OCORON", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
    assert not rs.is_credential(
        "N8N_WEBHOOK_CONTENT", "https://n8n.example/webhook/0123456789abcdef0123"
    )
    assert not rs.is_credential(
        "RESTIC_REPOSITORY", "s3:s3.us-west-004.backblazeb2.com/fabrik-restic-2026"
    )
    assert not rs.is_credential("M365_CERT_KEY_FILE", "/opt/fabrik/certs/m365-cert-2026.pem")
    assert not rs.is_credential("DNA_USER", "operator.name.2026.long.account")
    assert rs.is_credential("GOOGLE_ID_TOKEN", SECRET)
    assert rs.is_credential("WEBSHARE_HOST_AUTH", SECRET)


def test_kind_by_name_is_decidable_without_a_database():
    """The pure `is_credential` contract, guarded WITHOUT the local Postgres (17 of 18 tests here
    skip without it — AM3): an unanchored secret token + a knob value is config (AH1), a weak but
    real secret under an anchored name stays a credential (AM6), a scheme-less `user:pw@host`
    proxy is a credential whatever its `_PROXY` name says (AM7), `_PW`/`_CREDS` and numbered keys
    are anchored (AM8), and the fetcher rank is by role."""
    assert not rs.is_credential("WEBSHARE_IP_AUTH", "false")
    assert not rs.is_credential("X_AUTH_MODE", "basic")
    assert rs.is_credential("SOME_DSN", "postgres-secret-9f8e7d6c5b4a")
    assert rs.is_credential("DUPLICATI_PASSPHRASE", "1234")
    assert rs.is_credential("AUTHELIA_SESSION_SECRET", "changeme")
    assert rs.is_credential("B2_PROXY", "user:PaSsw0rdSecret@45.61.127.38:5977")
    assert not rs.is_credential("B2_PROXY", "45.61.127.38:5977")
    assert rs.is_credential("SMTP_HOST_PW", "S3cretPassw0rdLongEnough")
    assert rs.is_credential("DB_HOST_CREDS", "x")
    assert rs.is_credential("GROQ_API_KEY_2", "1234")
    assert not rs.is_credential(
        "GOOGLE_APPLICATION_CREDENTIALS", "/opt/fabrik/secrets/sa.json"
    )  # AM11
    assert rs.is_credential(
        "SOME_API_TOKEN", "/xk9m2p7q4z8w1n5aa"
    )  # one segment is not a path (AO1)
    assert not rs.is_credential(
        "UPLOAD_DIR", "/uploads2026-long-dir-name-x1"
    )  # mirror: a one-segment DIR is config by NAME
    assert rs.credential_rank("GROQ_API_KEY_2", "x") == 0
    assert rs.credential_rank("AZURE_ACCOUNT_NAME", "fabrikstorageaccount2026x1") == 2
    assert rs.credential_rank("NAMECHEAP_PROXY_URL", f"http://u:{SECRET}@h:1") == 3


def test_parse_fails_closed_on_an_unreadable_svc_line(tmp_path):
    """A `#svc` line SVC_RE cannot read (a model's `cost=free tier`) must never let the next
    provider's keys fall under the PREVIOUS provider — that pruned the provider, misattributed
    its keys and handed its secret to another vendor's credit fetcher (AP2). The sync raises."""
    f = tmp_path / "all-envs.env"
    f.write_text(
        "# " + "═" * 10 + " infra " + "═" * 10 + "\n"
        '#svc name=alpha category=infra cost=paid capability="a" url=https://a.example status=active used_by=p\n'
        "ALPHA_API_KEY=aaaa\n"
        '#svc name=bravo category=infra cost=free tier capability="b" url=https://b.example status=active used_by=p\n'
        "BRAVO_API_KEY=bbbb\n"
        '#svc name=charlie category=infra cost=paid capability="c" url=https://c.example status=active used_by=p\n'
        "CHARLIE_API_KEY=cccc\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unparseable #svc"):
        rs.parse(f)


def test_fetcher_rank_prefers_a_key_over_a_password_and_demotes_public_names():
    """21 of 24 live multi-credential providers tied at the old rank 0 and line order decided
    (AP3): a token/key outranks a password, a PUBLIC/ANON name is the last anchored resort, a
    non-URL value and a DSN follow; equal ranks break by the file's name-sorted order (stated)."""
    r = rs.credential_rank
    assert r("X_API_TOKEN", "v") < r("X_ADMIN_PASSWORD", "v")
    assert r("SUPABASE_SECRET_KEY", "v") < r("NEXT_PUBLIC_SUPABASE_ANON_KEY", "v")
    assert r("B2_APPLICATION_KEY", "v") < r("B2_ACCESS_KEY", "v")
    assert r("X_ADMIN_PASSWORD", "v") < r(
        "NEXT_PUBLIC_X_API_KEY", "v"
    )  # PUBLIC demotes a fetcher-grade name
    assert r("GRAFANA_SERVICE_ACCOUNT_TOKEN", "v") < r("GRAFANA_ADMIN_PASSWORD", "v")
    assert r("X_ADMIN_PASSWORD", "v") < r("X_ACCOUNT_NAME", "fabrikstorageaccount2026x1")
    assert r("X_ACCOUNT_NAME", "fabrikstorageaccount2026x1") < r("X_PROXY_URL", "http://u:p@h:1")
    # the regex boundaries (AP5/AP6/AP8)
    assert rs.is_credential("REDIS_URL", "redis://:Sup3rSecretPw@redis-main:6379")
    assert not rs.is_credential("X_NOTE", "sip:alice@example.com")
    assert not rs.is_credential("X_NOTE", "team:oncall@company.com")
    assert not rs.is_credential("TRAEFIK_BYPASS", "true")
    assert not rs.is_credential("SURVEY_MONKEY", "true")
    assert rs.is_credential("SMTP_HOST_PW", "S3cretPassw0rdLongEnough")
    # glued tokens stay anchored, the measured noise words do not (AS2/AP8); PUBLIC is bounded (AS8)
    assert rs.is_credential("SEDO_SIGNKEY", "1234")
    assert rs.is_credential("X_MASTERKEY", "1234") and rs.is_credential("X_DBPASS", "1234")
    assert not rs.is_credential("SURVEY_MONKEY", "true") and not rs.is_credential(
        "TRAEFIK_BYPASS", "true"
    )
    assert r("CANONICAL_API_KEY", "v") == 0 and r("NEXT_PUBLIC_X_API_KEY", "v") == 4
    assert r("SSH_PUBKEY", "v") == 4  # a glued public key is public too (AU8)
    # a public anon key is the LAST resort — below a real non-anchored secret and a DSN (AS9)
    assert r("X_SIGNATURE", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5") < r("NEXT_PUBLIC_X_API_KEY", "v")
    assert r("X_PROXY_URL", "http://u:p@h:1") < r("NEXT_PUBLIC_X_API_KEY", "v")


def test_equal_fetcher_ranks_break_by_file_order(fixture_env, monkeypatch):
    """Two rank-0 keys: the FIRST in file order feeds the fetcher — and the file is gather_envs'
    name-sorted output, so the rule is deterministic (AQ2: the docstring's tie clause, asserted)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " infra " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=infra cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_API_TOKEN={SECRET}first\n"
        f"{TEST_PROVIDER.upper()}_API_TOKEN_2={SECRET}second\n",
        encoding="utf-8",
    )
    got: list[tuple[str, str]] = []
    monkeypatch.setattr(rs, "fetch_balance", lambda name, value: got.append((name, value)) or None)
    rs.sync_registry(fetch_credits=True, prune=False)
    assert got == [(TEST_PROVIDER, f"{SECRET}first")], got


def test_a_merged_key_never_feeds_another_vendors_fetcher(fixture_env, monkeypatch):
    """One wrong model `name` merges `AAA_API_KEY` into deepl's block; it sorts first and ties at
    rank 0 — the fetcher must still get DEEPL's own key, and a block whose BEST credential is
    unowned gets no fetch at all (BH1)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " ai-translate " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=ai-translate cost=paid capability="test" '
        "url=https://deepl.com status=active used_by=projA\n"
        f"AAA_API_KEY={SECRET}victim\n"
        f"{TEST_PROVIDER.upper()}_API_KEY={SECRET}own\n"
        f'#svc name={TEST_PROVIDER2} category=search cost=paid capability="test" '
        "url=https://exa.ai status=active used_by=projA\n"
        f"BBB_API_KEY={SECRET}victim2\n",
        encoding="utf-8",
    )
    got: list[tuple[str, str]] = []
    monkeypatch.setattr(rs, "fetch_balance", lambda name, value: got.append((name, value)) or None)
    prov = (
        [
            (TEST_PROVIDER.upper(), TEST_PROVIDER),
            ("AAA", TEST_PROVIDER),
            ("BBB", TEST_PROVIDER2),
            (TEST_PROVIDER2.upper(), TEST_PROVIDER2),
        ],
        {("AAA", TEST_PROVIDER), ("BBB", TEST_PROVIDER2)},
    )
    monkeypatch.setattr(rs, "catalog_provenance", lambda: prov)  # what classify wrote
    rs.sync_registry(fetch_credits=True, prune=False)
    assert got == [(TEST_PROVIDER, f"{SECRET}own")], (
        got
    )  # exa's only credential is model-merged → no fetch
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT k.kind FROM api_keys k JOIN services s ON s.id=k.service_id WHERE s.provider='{TEST_PROVIDER2}' AND k.value_sha256=%s",
            (hashlib.sha256(f"{SECRET}victim2".encode()).hexdigest(),),
        )
        kinds = [r[0] for r in cur.fetchall()]
    conn.close()
    assert kinds == ["credential-unattributed"], kinds  # stored, visible, never a key (BK8)
    hf = (
        [("HF_TOKEN", "huggingface"), ("HUGGINGFACE", "huggingface"), ("HF", "huggingface")],
        {("HF", "huggingface")},
    )
    assert rs.owned_by(
        "HF_TOKEN", "huggingface", hf
    )  # the WINNING prefix is curated, the shorter merged one loses (BK3)
    assert not rs.owned_by("HF_API_KEY", "huggingface", hf)
    assert not rs.owned_by("AAA_API_KEY", TEST_PROVIDER, prov)
    assert not rs.owned_by(
        f"{TEST_PROVIDER.upper()}_API_KEY", TEST_PROVIDER, None
    )  # unknown provenance is never ownership (BK1)
    # a CURATED prefix of ANOTHER provider in this block is not ownership either — a stale block
    # carrying `DEEPL_API_KEY` under exa must never feed exa's fetcher (BM1)
    assert not rs.owned_by(f"{TEST_PROVIDER.upper()}_API_KEY", TEST_PROVIDER2, prov)
    # equal-length prefixes of TWO providers are a collision: owned by NEITHER, in both catalog
    # orders — the pass-19 grader here was `not X or order[0][1] == "zzz"`, true for the order
    # that exposed the stable-sort tie (BQ1)
    for order in ([("XY", "aaa"), ("XY", "zzz")], [("XY", "zzz"), ("XY", "aaa")]):
        both = (order, {("XY", "aaa")})
        assert not rs.owned_by("XY_API_KEY", "zzz", both), order
        assert not rs.owned_by("XY_API_KEY", "aaa", both), order
    assert not rs.owned_by(
        "XY_API_KEY", "aaa", ([("XY", "aaa"), ("XY", "zzz")], set())
    )  # unmerged tie: still nobody's
    # one vendor twice is no collision; a longer prefix still beats the tie
    assert rs.owned_by("XY_API_KEY", "aaa", ([("XY", "aaa"), ("XY", "aaa")], set()))
    assert rs.owned_by("XY_API_KEY", "zzz", ([("XY", "aaa"), ("XY_API", "zzz")], set()))


def test_an_unreadable_catalog_refuses_every_fetch_but_still_syncs(
    fixture_env, monkeypatch, tmp_path
):
    """Provenance UNKNOWN at sync time (the catalog file is unreadable): no key is attributable,
    so no credit fetch happens — but the DB sync itself proceeds (BK1/BK7)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " ai-translate " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=ai-translate cost=paid capability="test" '
        "url=https://deepl.com status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_API_KEY={SECRET}own\n",
        encoding="utf-8",
    )
    bad = tmp_path / "catalog.json"
    bad.write_text('{"truncated": ', encoding="utf-8")
    monkeypatch.setattr(rs.gather_envs, "CATALOG_PATH", bad)
    got: list[tuple[str, str]] = []
    monkeypatch.setattr(rs, "fetch_balance", lambda name, value: got.append((name, value)) or None)
    rs.sync_registry(fetch_credits=True, prune=False)
    assert got == [], got
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM services WHERE provider=%s", (TEST_PROVIDER,))
        assert cur.fetchone()[0] == 1  # the sync ran
    conn.close()
    bad.write_text('{"dee pl": {"category": "x"}}', encoding="utf-8")
    assert rs.catalog_provenance() is None  # an unround-trippable key: unknown, not an abort (BK7)


def test_unknown_provenance_is_said_once_and_exits_non_zero(
    fixture_env, monkeypatch, tmp_path, capsys
):
    """A degraded registry must not read LIVE: one summary line names the count and `main`
    returns 2 so the chain's _step alerts and skips the dashboard (BM2)."""
    fixture_env.write_text(
        "# " + "═" * 10 + " ai-translate " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=ai-translate cost=paid capability="test" '
        "url=https://deepl.com status=active used_by=projA\n"
        f"{TEST_PROVIDER.upper()}_API_KEY={SECRET}own\n",
        encoding="utf-8",
    )
    bad = tmp_path / "catalog.json"
    bad.write_text('{"truncated": ', encoding="utf-8")
    monkeypatch.setattr(rs.gather_envs, "CATALOG_PATH", bad)
    monkeypatch.setattr(sys, "argv", ["registry_sync.py"])
    real = rs.sync_registry
    monkeypatch.setattr(
        rs, "sync_registry", lambda **kw: real(prune=False, **kw)
    )  # the shared test registry must not be pruned
    assert rs.main() == 2
    err = capsys.readouterr().err
    assert "provenance UNKNOWN — 1 credential(s) stored unattributed" in err


def test_two_names_one_value_take_the_restrictive_kind_whatever_the_order(fixture_env, monkeypatch):
    """The same value under an owned name and an unattributed name collapses to ONE row (unique
    per digest): that row is `credential-unattributed` in both file orders (BM5)."""
    prov = (
        [(TEST_PROVIDER.upper(), TEST_PROVIDER), ("AAA", TEST_PROVIDER)],
        {("AAA", TEST_PROVIDER)},
    )
    monkeypatch.setattr(rs, "catalog_provenance", lambda: prov)
    for first, second in (
        ("AAA_API_KEY", f"{TEST_PROVIDER.upper()}_API_KEY"),
        (f"{TEST_PROVIDER.upper()}_API_KEY", "AAA_API_KEY"),
    ):
        fixture_env.write_text(
            "# " + "═" * 10 + " ai-translate " + "═" * 10 + "\n"
            f'#svc name={TEST_PROVIDER} category=ai-translate cost=paid capability="test" '
            "url=https://deepl.com status=active used_by=projA\n"
            f"{first}={SECRET}same\n"
            f"{second}={SECRET}same\n",
            encoding="utf-8",
        )
        rs.sync_registry(fetch_credits=False, prune=False)
        conn = rdb.connect()
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT kind FROM api_keys WHERE value_sha256=%s",
                (hashlib.sha256(f"{SECRET}same".encode()).hexdigest(),),
            )
            kinds = [r[0] for r in cur.fetchall()]
        conn.close()
        assert kinds == ["credential-unattributed"], (first, kinds)


def test_an_empty_catalog_is_known_provenance_not_unknown(tmp_path, monkeypatch):
    """`{}` is a catalog with nothing curated and nothing merged — every key is its derived block's
    own and `main` exits 0; only an UNREADABLE catalog is unknown (exit 2). Conflating them made a
    bootstrap registry page every day forever (BR3)."""
    empty = tmp_path / "catalog.json"
    empty.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(rs.gather_envs, "CATALOG_PATH", empty)
    assert rs.catalog_provenance() == ([], set())
    assert rs.owned_by("FOO_API_KEY", "foo", rs.catalog_provenance())
    empty.write_text("[]", encoding="utf-8")
    assert rs.catalog_provenance() is None  # not an object: unknown (BH6)
    empty.write_text("{", encoding="utf-8")
    assert rs.catalog_provenance() is None  # unreadable: unknown (BK1)


def test_two_names_one_value_union_their_projects_whatever_the_order(fixture_env, monkeypatch):
    """Two names carrying one value are ONE row (unique per digest); its `used_by_projects` is the
    union of both names' attribution in either file order — the last name alone dropped projects
    on 2 live rows (BR6)."""
    tp = TEST_PROVIDER.upper()
    for first, second in ((f"{tp}_HOST", f"{tp}_HOST_ALT"), (f"{tp}_HOST_ALT", f"{tp}_HOST")):
        fixture_env.write_text(
            "# " + "═" * 10 + " ai-llm " + "═" * 10 + "\n"
            f'#svc name={TEST_PROVIDER} category=ai-llm cost=paid capability="test" '
            "url=https://x.example status=active used_by=projA,projB\n"
            f"{first}=same.host.example   # used by: projA\n"
            f"{second}=same.host.example   # used by: projB\n",
            encoding="utf-8",
        )
        rs.sync_registry(fetch_credits=False, prune=False)
        conn = rdb.connect()
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT k.used_by_projects, k.aliases FROM api_keys k JOIN services s ON s.id=k.service_id "
                "WHERE s.provider=%s AND k.value_sha256=%s",
                (TEST_PROVIDER, hashlib.sha256(b"same.host.example").hexdigest()),
            )
            rows = cur.fetchall()
        conn.close()
        assert [tuple(r[0]) for r in rows] == [("projA", "projB")], (first, rows)
