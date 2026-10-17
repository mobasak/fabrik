"""The snapshot token: what a decision card looked like when the operator read it (plan 2026-10-17-plan-1, T02).

A card carries `token(item)` of the item it was rendered from; a verdict POST sends it back, and the
server refuses it with 409 when the item as it stands now gives a different token — the question, the
status, the ground, the comment count or the merged duplicates moved under the operator's eyes. The
token is the first 16 hex characters of sha256 over the JSON of exactly those five readings, missing
ones as ``None``, ``0`` and ``[]``.

Cobra check (D-253): the cheapest way to pass "a changed item is refused" without the outcome is a
token over fields nothing ever changes (the id, the title). The five readings are the ones a decision
rests on; the server tests change each one and watch the 409.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

__all__ = ["token"]


def token(item: Mapping[str, object]) -> str:
    """16 hex characters naming the item's question, status, ground, comment count and alt ids."""
    comments = item.get("comments")
    alt = item.get("alt_ids")
    alt = [] if alt is None else alt
    reading = [
        item.get("question"),
        item.get("status"),
        item.get("ground"),
        len(comments) if isinstance(comments, (list, tuple)) else 0,
        # a list sorts by (type, text), so mixed ids never raise and either order agrees; anything
        # else (a hand-edited string, an object) is its own JSON value, never a silent []
        sorted(alt, key=lambda a: (type(a).__name__, str(a)))
        if isinstance(alt, (list, tuple))
        else alt,
    ]
    raw = json.dumps(
        reading, separators=(",", ":"), ensure_ascii=False, sort_keys=True, default=str
    )
    return hashlib.sha256(raw.encode("utf-8", "surrogatepass")).hexdigest()[:16]
