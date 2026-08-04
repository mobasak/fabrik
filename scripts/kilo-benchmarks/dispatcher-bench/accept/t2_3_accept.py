import pytest

from app import orders, store


def _mk(status=None):
    o = orders.create_order("u1", "widget", 40.0)
    if status:
        store.ORDERS[o["id"]]["status"] = status
    return o


def test_b1_pending_cancels_free():
    store.reset()
    o = _mk()
    assert orders.cancel_order(o["id"])["fee"] == 0.0
    assert store.ORDERS[o["id"]]["status"] == "cancelled"


def test_b2_paid_cancels_with_10pct_fee():
    store.reset()
    o = _mk("paid")
    assert orders.cancel_order(o["id"])["fee"] == 4.0


def test_b3_shipped_cancel_rejected():
    store.reset()
    o = _mk("shipped")
    with pytest.raises(ValueError):
        orders.cancel_order(o["id"])


def test_b4_already_cancelled_idempotent():
    store.reset()
    o = _mk()
    orders.cancel_order(o["id"])
    n = len(store.SENT)
    assert orders.cancel_order(o["id"])["fee"] == 0.0
    assert len(store.SENT) == n  # no duplicate notification


def test_b5_unknown_id_keyerror():
    store.reset()
    with pytest.raises(KeyError):
        orders.cancel_order("ord_nope")


def test_b6_exactly_one_notification():
    store.reset()
    o = _mk()
    before = len(store.SENT)
    orders.cancel_order(o["id"])
    sent = [s for s in store.SENT[before:] if f"order {o['id']} cancelled" in s["message"]]
    assert len(sent) == 1
