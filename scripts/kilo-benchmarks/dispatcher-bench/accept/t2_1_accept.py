import pytest

from app import billing, store


def test_over_refund_rejected():
    store.reset()
    c = billing.charge("o1", 20.0)
    billing.refund(c["charge_id"], 15.0)
    with pytest.raises(ValueError):
        billing.refund(c["charge_id"], 10.0)  # only 5.0 remains
    store.reset()


def test_refund_within_remaining_ok():
    store.reset()
    c = billing.charge("o1", 20.0)
    billing.refund(c["charge_id"], 15.0)
    r = billing.refund(c["charge_id"], 5.0)
    assert r["refunded"] == 20.0
    store.reset()
