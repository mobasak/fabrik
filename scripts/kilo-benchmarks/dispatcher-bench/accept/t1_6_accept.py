from app import notify, orders, store


def test_get_order_or_none_present():
    store.reset()
    o = orders.create_order("u", "widget", 1.0)
    assert orders.get_order_or_none(o["id"])["id"] == o["id"]
    assert orders.get_order_or_none("ord_none") is None


def test_format_order_ref_missing_order():
    store.reset()
    assert notify.format_order_ref("ord_none") == "unknown order ord_none"
