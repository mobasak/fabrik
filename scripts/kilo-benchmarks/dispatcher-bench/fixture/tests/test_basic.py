"""Baseline behaviours (green on main)."""
import pytest

from app import auth, billing, orders, status, store


@pytest.fixture(autouse=True)
def clean():
    store.reset()
    yield
    store.reset()


def test_create_and_get():
    o = orders.create_order("u1", "widget", 9.5)
    assert orders.get_order(o["id"])["item"] == "widget"


def test_status_transition():
    o = orders.create_order("u1", "widget", 9.5)
    orders.set_status(o["id"], "paid")
    assert orders.get_order(o["id"])["status"] == "paid"
    with pytest.raises(ValueError):
        orders.set_status(o["id"], "pending")


def test_status_labels():
    assert status.label("pending") == "Pending"


def test_charge_and_refund():
    o = orders.create_order("u1", "widget", 20.0)
    c = billing.charge(o["id"], 20.0, idempotency_key="k1")
    r = billing.refund(c["charge_id"], 5.0)
    assert r["refunded"] == 5.0


def test_auth_issue_refresh():
    t = auth.issue("u1")
    t2 = auth.refresh(t["refresh"])
    assert t2["access"] != t["access"]
