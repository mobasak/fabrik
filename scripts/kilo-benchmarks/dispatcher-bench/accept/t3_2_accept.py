import pytest

from app import notify, orders, status, store


def test_refunded_in_statuses():
    assert "refunded" in status.STATUSES


def test_transitions_paid_and_shipped_to_refunded():
    assert status.can_transition("paid", "refunded")
    assert status.can_transition("shipped", "refunded")
    assert not status.can_transition("pending", "refunded")
    assert not status.can_transition("refunded", "paid")


def test_label_and_notify():
    assert status.label("refunded") == "Refunded"
    store.reset()
    o = orders.create_order("u1", "w", 10.0)
    orders.set_status(o["id"], "paid")
    orders.set_status(o["id"], "refunded")
    assert store.SENT[-1]["message"].endswith("is now Refunded")


def test_full_transition_via_orders():
    store.reset()
    o = orders.create_order("u1", "w", 10.0)
    orders.set_status(o["id"], "paid")
    orders.set_status(o["id"], "shipped")
    orders.set_status(o["id"], "refunded")
    with pytest.raises(ValueError):
        orders.set_status(o["id"], "paid")
