"""Unit tests for fabrik.orchestrator.sysadmin_tokens (PR3 token pool).

DR store redirected to a tmp path via FABRIK_DR_STORE; no real DR-store writes.
Covers the C4 hygiene contract: claim/no-double-assign/idempotent-reclaim,
empty-pool -> None (so the caller skips enabling the bot), release round-trip.
"""

import json

import pytest

from fabrik.orchestrator import sysadmin_tokens as st


@pytest.fixture(autouse=True)
def _tmp_dr_store(tmp_path, monkeypatch):
    monkeypatch.setenv("FABRIK_DR_STORE", str(tmp_path))
    yield


def _seed_pool(entries):
    p = st.pool_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema_version": 1, "pool": entries}))


def test_empty_pool_returns_none_not_placeholder():
    # No pool file at all -> empty -> None (caller MUST skip enabling the bot).
    assert st.claim_bot_token("vps4") is None
    assert st.pool_status() == {"total": 0, "assigned": 0, "free": 0}


def test_claim_assigns_first_free_and_stamps():
    _seed_pool([
        {"token": "111:tok-A", "label": "VPS4", "assigned_to": None, "assigned_at": None},
        {"token": "222:tok-B", "label": "VPS5", "assigned_to": None, "assigned_at": None},
    ])
    assert st.claim_bot_token("vps4") == "111:tok-A"
    pool = json.loads(st.pool_path().read_text())["pool"]
    assert pool[0]["assigned_to"] == "vps4" and pool[0]["assigned_at"] is not None
    assert pool[1]["assigned_to"] is None  # untouched
    assert st.pool_status() == {"total": 2, "assigned": 1, "free": 1}


def test_no_double_assign_across_hosts():
    _seed_pool([
        {"token": "111:tok-A", "label": "VPS4", "assigned_to": None, "assigned_at": None},
        {"token": "222:tok-B", "label": "VPS5", "assigned_to": None, "assigned_at": None},
    ])
    assert st.claim_bot_token("vps4") == "111:tok-A"
    assert st.claim_bot_token("vps5") == "222:tok-B"  # gets the NEXT free, never T1


def test_idempotent_reclaim_returns_same_token():
    _seed_pool([{"token": "111:tok-A", "label": "VPS4", "assigned_to": None, "assigned_at": None}])
    first = st.claim_bot_token("vps4")
    second = st.claim_bot_token("vps4")  # re-run of provision for same host
    assert first == second == "111:tok-A"
    assert st.pool_status()["assigned"] == 1  # not double-counted


def test_exhausted_pool_returns_none():
    _seed_pool([{"token": "111:tok-A", "label": "VPS4", "assigned_to": "vps4", "assigned_at": "t"}])
    assert st.claim_bot_token("vps5") is None  # only entry is taken by someone else


def test_release_returns_slot_to_pool():
    _seed_pool([{"token": "111:tok-A", "label": "VPS4", "assigned_to": "vps4", "assigned_at": "t"}])
    assert st.release_bot_token("vps4") is True
    assert st.pool_status() == {"total": 1, "assigned": 0, "free": 1}
    # released slot is claimable again
    assert st.claim_bot_token("vps9") == "111:tok-A"


def test_release_noop_when_not_assigned():
    _seed_pool([{"token": "111:tok-A", "label": "VPS4", "assigned_to": None, "assigned_at": None}])
    assert st.release_bot_token("vps4") is False


def test_malformed_token_skipped_never_assigned():
    """PR3-review hardening: a malformed/typo'd token must never be assigned (it
    would be interpolated into the .env.sysadmin sed). Skip it, take the next valid."""
    _seed_pool([
        {"token": "not-a-real-token", "label": "BAD", "assigned_to": None, "assigned_at": None},
        {"token": "333:tok-C", "label": "VPS6", "assigned_to": None, "assigned_at": None},
    ])
    assert st.claim_bot_token("vps6") == "333:tok-C"  # skipped the malformed entry
    pool = json.loads(st.pool_path().read_text())["pool"]
    assert pool[0]["assigned_to"] is None  # malformed entry left untouched


def test_all_malformed_pool_returns_none():
    _seed_pool([{"token": "bogus", "label": "BAD", "assigned_to": None, "assigned_at": None}])
    assert st.claim_bot_token("vps6") is None  # nothing valid to assign -> bot skipped
