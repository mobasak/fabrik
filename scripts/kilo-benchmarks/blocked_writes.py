"""Persistent review queue for safety-blocked direct-vendor writes.

When `fetch_direct_vendor_prices.py` refuses to write a price update
(typically because parsed vs DB drift > 50% — a real safety guard that
prevents a scraper regression from corrupting the DB), the blocked delta
was previously only logged to `update.log` and silently dropped. Result:
operators had no queue to review + reconcile (either apply the change
manually if the parser is wrong, or update the parser if the vendor
changed pricing).

Plan-4 Phase D fix: append every blocked write to
`scripts/kilo-benchmarks/cache/blocked_writes/YYYY-MM-DD.md`. Idempotent
within a day so repeat blocks on the same (vendor, model_id, prices)
tuple don't duplicate the row.
"""

# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_blocked_writes.py

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

_CACHE_DIR = Path(__file__).parent / "cache" / "blocked_writes"

_HEADER = (
    "| vendor | model_id | parsed | db | reason | raw (truncated) |\n|---|---|---:|---:|---|---|\n"
)


def _new_file_header(today: _dt.date) -> str:
    return (
        f"# Blocked direct-vendor writes — {today.isoformat()}\n\n"
        "Each row is a parsed price update that failed the safety guard. Review "
        "weekly and either update the parser or apply the change manually.\n\n"
    ) + _HEADER


def record_blocked_write(
    vendor: str,
    model_id: str,
    parsed_price: float,
    db_price: float,
    reason: str,
    raw_text: str,
    *,
    today: _dt.date | None = None,
) -> Path:
    """Append one row to today's blocked-writes MD.

    Idempotent per `(vendor, model_id, parsed_price, db_price, day)` tuple —
    the same block observed twice in one day writes ONE row.
    """
    today = today or _dt.date.today()
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = _CACHE_DIR / f"{today.isoformat()}.md"

    key = f"| {vendor} | {model_id} | ${parsed_price:.4f} | ${db_price:.4f} |"
    if out.exists():
        if key in out.read_text(encoding="utf-8"):
            return out
    else:
        out.write_text(_new_file_header(today), encoding="utf-8")

    # Truncate + escape pipes / newlines / tabs in raw_text so we can't
    # corrupt the markdown table (same substitution rule as audit_pipeline.py).
    raw = re.sub(r"\s+", " ", (raw_text or "")[:80]).replace("|", "¦")
    with out.open("a", encoding="utf-8") as f:
        f.write(f"{key} {reason} | `{raw}` |\n")
    return out
