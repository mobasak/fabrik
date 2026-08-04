"""Order CRUD + listing."""
from __future__ import annotations

import itertools

from app import notify, status, store

_seq = itertools.count(1)


def create_order(user: str, item: str, amount: float) -> dict:
    oid = f"ord_{next(_seq):05d}"
    order = {
        "id": oid,
        "user": user,
        "item": item,
        "amount": float(amount),
        "status": "pending",
        "created_at": len(store.ORDERS),  # monotonic insertion index
    }
    store.ORDERS[oid] = order
    notify.send(user, f"order {oid} created")
    return order


def get_order(order_id: str) -> dict:
    return store.ORDERS[order_id]


def set_status(order_id: str, new_status: str) -> dict:
    order = get_order(order_id)
    if not status.can_transition(order["status"], new_status):
        raise ValueError(f"illegal transition {order['status']} -> {new_status}")
    order["status"] = new_status
    notify.send(order["user"], notify.format_status_update(order, new_status))
    return order


def list_orders(page: int = 1, per_page: int = 10) -> list[dict]:
    """Return one page of orders in creation order."""
    items = sorted(store.ORDERS.values(), key=lambda o: o["created_at"])
    start = (page - 1) * per_page
    return items[start : start + per_page - 1]
