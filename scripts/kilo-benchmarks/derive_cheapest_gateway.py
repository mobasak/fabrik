#!/usr/bin/env python3
"""Derive `cheapest_gateway` and `cheapest_gateway_price` from `gateway_prices`.

The `agents.gateway_prices` JSON column (populated by Phase 1 Replicate and
Phase 2 fal.ai fetchers) holds a map of gateway → {price, unit, confidence,
...}. This script picks the cheapest entry whose `unit` matches the row's
`pricing_unit` (apples-to-apples) AND whose `confidence` is >= 0.5
(skipping fal.ai null-price entries flagged with confidence=0).

The DIRECT-vendor price (`input_cost_per_m` + `pricing_unit` on the row
itself) is included as a candidate gateway named `direct`. If `direct`
is the cheapest, that's the answer.

Writes:
  cheapest_gateway       TEXT  — name of the winning gateway ('direct'|'replicate'|'fal_ai'|...)
  cheapest_gateway_price REAL  — that gateway's normalized $/M-billable-units

Rows with NO usable gateway entries (gateway_prices NULL OR no confidence>=0.5
entries with matching unit) get both columns set to NULL.

Idempotent: re-running with the same inputs writes the same outputs.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

MIN_CONFIDENCE = 0.5
# Gateway entries older than this lose eligibility — they probably came
# from a stale mirror-map entry that has since been removed. Adversarial
# review Pass 1 Finding A: without this check, removing a row from
# replicate_mirrors.yaml leaves orphan entries in gateway_prices that
# can win derive_row forever.
MAX_AGE_DAYS = 30


def _log(msg: str) -> None:
    print(f"[derive_cheapest_gateway] {msg}")


def _is_recent(last_seen: str | None, today: date | None = None) -> bool:
    """Adversarial Pass 1 Finding A: gateway entries lose eligibility once
    older than MAX_AGE_DAYS. Without this guard a row removed from the
    mirror map leaves orphan entries that win derive_row forever."""
    if not last_seen:
        return False
    try:
        seen = date.fromisoformat(last_seen)
    except (TypeError, ValueError):
        return False
    today = today or datetime.now(UTC).date()
    return (today - seen) <= timedelta(days=MAX_AGE_DAYS)


def derive_row(
    gateway_prices_json: str | None,
    direct_price: float | None,
    direct_unit: str | None,
    today: date | None = None,
    kilo_price: float | None = None,
    kilo_cache_read_price: float | None = None,
    direct_cache_read_price: float | None = None,
) -> tuple[str | None, float | None]:
    """Pure function: pick cheapest gateway+price for a single row.

    Returns (cheapest_gateway_name, cheapest_price). Either both None or both set.

    Apples-to-apples rule: candidate entries MUST share the same unit as
    `direct_unit`. If `direct_unit` is None we refuse to derive (Pass 1
    Finding B — comparing image to video-sec is a category error).

    2026-07-01: Kilo Gateway added as a gateway candidate. When
    `kilo_input_cost_per_m` differs from the OR (`direct`) price by more
    than $0.005/M, whichever is lower wins. Fixes the operator-reported
    "Kilo is cheaper for qwen3.6-plus but cheapest_gateway=direct".

    2026-07-01: cache-read pricing also considered — for production workloads
    with repeat prompts the cache-hit price is the operative rate, and Kilo
    vs OR can diverge there too.
    """
    if not direct_unit:
        # Pass 1 Finding B: no canonical unit on the row → no safe comparison.
        return None, None
    candidates: list[tuple[str, float]] = []
    if direct_price is not None and direct_price > 0:
        candidates.append(("direct", direct_price))
    # Kilo Gateway: same-unit by construction (Kilo prices are always M-tokens
    # for LLMs — Kilo-only STT/TTS/etc. rows don't have kilo_input_cost_per_m
    # set). Include only if meaningfully different from direct so we don't
    # promote a floating-point-precision tie.
    if kilo_price is not None and kilo_price > 0:
        if direct_price is None or abs(kilo_price - direct_price) > 0.005:
            candidates.append(("kilo", kilo_price))
    if gateway_prices_json:
        try:
            gp = json.loads(gateway_prices_json)
        except (json.JSONDecodeError, TypeError):
            gp = {}
        for gateway_name, entry in (gp or {}).items():
            if not isinstance(entry, dict):
                continue
            confidence = entry.get("confidence", 1.0)
            price = entry.get("price")
            unit = entry.get("unit")
            last_seen = entry.get("last_seen")
            if price is None or confidence is None or confidence < MIN_CONFIDENCE:
                continue
            # Apples-to-apples: enforce same unit. Pass 1 Finding B fix.
            if unit != direct_unit:
                continue
            # Pass 1 Finding A: drop stale entries (mirror map shrank).
            if not _is_recent(last_seen, today):
                continue
            try:
                price_f = float(price)
            except (TypeError, ValueError):
                continue
            if price_f <= 0:
                continue
            candidates.append((gateway_name, price_f))
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[1])
    return candidates[0]


def run(db_path: Path = DB_PATH) -> dict[str, int]:
    counts = {"rows_with_gateways": 0, "rows_with_direct_only": 0, "winners_by_gateway": {}}
    conn = sqlite3.connect(db_path)
    try:
        # Pass 2 Finding F4: explicit transaction for atomicity.
        conn.execute("BEGIN")
        rows = conn.execute(
            "SELECT id, gateway_prices, input_cost_per_m, pricing_unit, kilo_input_cost_per_m "
            "FROM agents WHERE status = 'active'"
        ).fetchall()
        for agent_id, gp_json, direct_price, direct_unit, kilo_price in rows:
            # Every row with a real price + canonical unit gets `direct` as
            # the trivial cheapest when no mirror data exists. Previously
            # we skipped these rows entirely — the column showed "—" for
            # ~96% of the catalog, which was confusing. Now Cheapest =
            # min(direct, replicate, fal_ai, ...) and is always populated
            # whenever the row has a direct price to begin with.
            if gp_json:
                counts["rows_with_gateways"] += 1
            elif direct_price and direct_price > 0 and direct_unit:
                counts["rows_with_direct_only"] += 1
            else:
                continue
            winner_name, winner_price = derive_row(
                gp_json, direct_price, direct_unit, kilo_price=kilo_price
            )
            conn.execute(
                "UPDATE agents SET cheapest_gateway = ?, cheapest_gateway_price = ? WHERE id = ?",
                (winner_name, winner_price, agent_id),
            )
            if winner_name:
                counts["winners_by_gateway"][winner_name] = (
                    counts["winners_by_gateway"].get(winner_name, 0) + 1
                )
        conn.commit()
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    counts = run(args.db)
    _log(f"summary: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
