"""User notifications. Delivery is a stub: messages land in store.SENT."""
from __future__ import annotations

from app import status, store


def send(user: str, message: str) -> None:
    store.SENT.append({"user": user, "message": message})


def format_status_update(order: dict, new_status: str) -> str:
    return f"order {order['id']} is now {status.label(new_status)}"


def format_order_ref(order_id: str) -> str:
    from app import orders

    order = orders.get_order(order_id)
    return f"{order['id']} ({order['item']})"
