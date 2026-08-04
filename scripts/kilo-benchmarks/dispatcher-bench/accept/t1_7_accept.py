from app import orders, store


def test_pagination_full_coverage():
    store.reset()
    for i in range(25):
        orders.create_order("u", f"item{i}", 1.0)
    pages = [orders.list_orders(page=p, per_page=10) for p in (1, 2, 3)]
    assert [len(p) for p in pages] == [10, 10, 5]
    ids = {o["id"] for page in pages for o in page}
    assert len(ids) == 25
    store.reset()


def test_pagination_exact_boundary():
    store.reset()
    for i in range(20):
        orders.create_order("u", f"i{i}", 1.0)
    assert len(orders.list_orders(page=2, per_page=10)) == 10
    assert orders.list_orders(page=3, per_page=10) == []
    store.reset()
