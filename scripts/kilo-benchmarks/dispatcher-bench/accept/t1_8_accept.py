from app import billing, store


def test_same_key_returns_original_charge():
    store.reset()
    c1 = billing.charge("o1", 10.0, idempotency_key="k1")
    c2 = billing.charge("o1", 10.0, idempotency_key="k1")
    assert c1["charge_id"] == c2["charge_id"]
    assert len(store.CHARGES) == 1
    store.reset()


def test_distinct_keys_charge_twice():
    store.reset()
    billing.charge("o1", 10.0, idempotency_key="a")
    billing.charge("o1", 10.0, idempotency_key="b")
    assert len(store.CHARGES) == 2
    store.reset()


def test_no_key_always_charges():
    store.reset()
    billing.charge("o1", 10.0)
    billing.charge("o1", 10.0)
    assert len(store.CHARGES) == 2
    store.reset()
