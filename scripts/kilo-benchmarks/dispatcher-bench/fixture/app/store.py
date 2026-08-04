"""In-memory data store standing in for the shared Postgres in this exercise repo."""
from __future__ import annotations

ORDERS: dict[str, dict] = {}
JOBS: list[dict] = []  # FIFO pending-job queue
CHARGES: list[dict] = []
SENT: list[dict] = []  # notification outbox (tests inspect this)


def reset() -> None:
    ORDERS.clear()
    JOBS.clear()
    CHARGES.clear()
    SENT.clear()
