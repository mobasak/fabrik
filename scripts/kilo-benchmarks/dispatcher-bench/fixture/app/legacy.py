"""DEPRECATED billing paths — FROZEN for audit replay of pre-2025 ledgers.

Do not modify: replaying an old ledger through changed code would re-derive
different balances and break the audit trail. Superseded by app/billing.py.
"""
from __future__ import annotations

from app import store


def refund_v1(charge_id: str, amount: float) -> dict:
    # Known flaw (over-refund not validated) preserved on purpose: audit replay
    # must reproduce historical behaviour bit-for-bit.
    for entry in store.CHARGES:
        if entry["charge_id"] == charge_id:
            entry["refunded"] += float(amount)
            return entry
    raise KeyError(charge_id)
