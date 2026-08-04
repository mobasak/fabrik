from app import billing, orders, store


def test_all_sent_entries_carry_severity():
    store.reset()
    orders.create_order("u1", "w", 10.0)
    assert all("severity" in s for s in store.SENT)


def test_create_is_info():
    store.reset()
    orders.create_order("u1", "w", 10.0)
    assert store.SENT[-1]["severity"] == "info"


def test_refund_is_warning():
    store.reset()
    o = orders.create_order("u1", "w", 10.0)
    c = billing.charge(o["id"], 10.0)
    billing.refund(c["charge_id"], 5.0)
    assert store.SENT[-1]["severity"] == "warning"


def test_cancelled_transition_is_warning():
    store.reset()
    o = orders.create_order("u1", "w", 10.0)
    orders.set_status(o["id"], "cancelled")
    assert store.SENT[-1]["severity"] == "warning"


def test_paid_transition_is_info():
    store.reset()
    o = orders.create_order("u1", "w", 10.0)
    orders.set_status(o["id"], "paid")
    assert store.SENT[-1]["severity"] == "info"
