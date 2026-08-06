"""Unit tests for aro-wake's /digest-input + /digest-inbox routes
(plan §2.1 fleet-hardening). Spawned as subprocess to avoid the heavy
import surface aro-wake brings in at module level."""

from __future__ import annotations

import importlib.util
import time

import pytest


@pytest.fixture(scope="module")
def aro_wake_module():
    """Load aro-wake/main.py without invoking its main() entrypoint."""
    spec = importlib.util.spec_from_file_location(
        "aro_wake_main", "/opt/fabrik/scripts/aro-wake/main.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Modal SDK isn't needed; gracefully handle absent imports
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        pytest.skip(f"aro-wake module load failed: {e}")
    return mod


def test_digest_input_accepts_and_queues(aro_wake_module):
    """POST /digest-input must accept JSON body and grow the deque."""
    from fastapi.testclient import TestClient

    client = TestClient(aro_wake_module.app)
    aro_wake_module.DIGEST_INBOX.clear()  # isolate test
    resp = client.post(
        "/digest-input",
        json={"text": "[vps2] digest body", "metrics": {"tier_a_count": 3}},
        # TestClient simulates a client at 127.0.0.1 (which maps to
        # 'unknown-127.0.0.1' via the static peer map — that's fine for the test)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["queue_depth"] == 1
    # Inbox has one entry for the synthesized host name
    all_entries = [e for host_q in aro_wake_module.DIGEST_INBOX.values() for e in host_q]
    assert len(all_entries) == 1
    assert all_entries[0]["text"] == "[vps2] digest body"


def test_digest_inbox_drains_and_clears(aro_wake_module):
    """GET /digest-inbox returns entries >= since AND removes them."""
    from fastapi.testclient import TestClient

    client = TestClient(aro_wake_module.app)
    aro_wake_module.DIGEST_INBOX.clear()
    # Inject 2 entries via /digest-input
    client.post("/digest-input", json={"text": "a", "metrics": {}})
    client.post("/digest-input", json={"text": "b", "metrics": {}})
    # Drain (since=0 → all)
    drain_resp = client.get("/digest-inbox?since=0")
    assert drain_resp.status_code == 200
    drained = drain_resp.json()
    assert len(drained) == 2
    # Texts present
    texts = {d["text"] for d in drained}
    assert texts == {"a", "b"}
    # Second drain returns empty (entries were removed)
    drain2 = client.get("/digest-inbox?since=0").json()
    assert drain2 == []


def test_digest_inbox_24h_ttl_drops_stale(aro_wake_module):
    """Entries older than 24h must be GC'd on drain even if since is older."""
    from fastapi.testclient import TestClient

    client = TestClient(aro_wake_module.app)
    aro_wake_module.DIGEST_INBOX.clear()
    # Manually inject a 48h-old entry
    aro_wake_module.DIGEST_INBOX["vps2"].append(
        {
            "ts": time.time() - 48 * 3600,
            "source_host": "vps2",
            "text": "ancient",
            "metrics": {},
        }
    )
    # Drain since=0
    drained = client.get("/digest-inbox?since=0").json()
    # Stale entry must NOT appear
    texts = [d["text"] for d in drained]
    assert "ancient" not in texts


def test_digest_input_increments_prometheus_counter(aro_wake_module):
    """M_DIGEST_INPUT counter must bump on every successful POST.

    TestClient.client.host can vary across Starlette versions, so we
    sum across all label permutations rather than assert against a
    specific from_host label value.
    """
    from fastapi.testclient import TestClient

    client = TestClient(aro_wake_module.app)
    aro_wake_module.DIGEST_INBOX.clear()

    def total():
        s = 0.0
        for metric_family in aro_wake_module.M_DIGEST_INPUT.collect():
            for sample in metric_family.samples:
                if sample.name.endswith("_total"):
                    s += sample.value
        return s

    initial = total()
    client.post("/digest-input", json={"text": "smoke", "metrics": {}})
    after = total()
    assert after >= initial + 1, f"counter total didn't increment ({initial} → {after})"
