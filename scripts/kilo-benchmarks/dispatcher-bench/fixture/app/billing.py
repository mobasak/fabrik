"""Charges and refunds."""
from __future__ import annotations

from app import notify, store


def charge(order_id: str, amount: float, idempotency_key: str | None = None) -> dict:
    entry = {
        "charge_id": f"ch_{len(store.CHARGES) + 1:05d}",
        "order_id": order_id,
        "amount": float(amount),
        "idempotency_key": idempotency_key,
        "refunded": 0.0,
    }
    store.CHARGES.append(entry)
    return entry


def refund(charge_id: str, amount: float) -> dict:
    for entry in store.CHARGES:
        if entry["charge_id"] == charge_id:
            entry["refunded"] += float(amount)
            order = store.ORDERS.get(entry["order_id"])
            if order:
                notify.send(order["user"], f"refund {amount} on {charge_id}")
            return entry
    raise KeyError(charge_id)
