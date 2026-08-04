"""Order status model: allowed values, transitions, display labels."""
from __future__ import annotations

STATUSES = ("pending", "paid", "shipped", "cancelled")

_TRANSITIONS = {
    "pending": {"paid", "cancelled"},
    "paid": {"shipped", "cancelled"},
    "shipped": set(),
    "cancelled": set(),
}

_LABELS = {
    "pending": "Pending",
    "paid": "Paid",
    "shipped": "Shipped",
    "cancelled": "Cancelled",
}


def can_transition(current: str, new: str) -> bool:
    return new in _TRANSITIONS.get(current, set())


def label(s: str) -> str:
    return _LABELS[s]
