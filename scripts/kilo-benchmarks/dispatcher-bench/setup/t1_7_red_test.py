"""CI regression test — added by the platform team. Do not modify."""
from app import orders, store


def test_pagination_pages_cover_all():
    store.reset()
    for i in range(25):
        orders.create_order("u", f"item{i}", 1.0)
    p1 = orders.list_orders(page=1, per_page=10)
    p2 = orders.list_orders(page=2, per_page=10)
    p3 = orders.list_orders(page=3, per_page=10)
    assert [len(p1), len(p2), len(p3)] == [10, 10, 5]
    ids = {o["id"] for o in p1 + p2 + p3}
    assert len(ids) == 25
    store.reset()
