import csv

from app import export, orders, store


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_header_and_order(tmp_path):
    store.reset()
    orders.create_order("u1", "widget", 3.5)
    p = tmp_path / "o.csv"
    export.to_csv(list(store.ORDERS.values()), p)
    rows = _rows(p)
    assert rows[0] == ["id", "user", "item", "amount", "status"]
    assert len(rows) == 2
    store.reset()


def test_quoting_round_trips(tmp_path):
    store.reset()
    orders.create_order('u,1', 'wid"get', 3.5)
    orders.create_order("u2", "multi\nline", 1.0)
    p = tmp_path / "o.csv"
    export.to_csv(list(store.ORDERS.values()), p)
    rows = _rows(p)
    assert rows[1][1] == "u,1" and rows[1][2] == 'wid"get'
    assert rows[2][2] == "multi\nline"
    store.reset()


def test_empty_list_header_only(tmp_path):
    p = tmp_path / "o.csv"
    export.to_csv([], p)
    assert _rows(p) == [["id", "user", "item", "amount", "status"]]
