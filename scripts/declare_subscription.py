#!/usr/bin/env python3
# AFTER-EDIT: db/services_registry_schema.sql
"""Declare a subscription (renewal date / price / account email) for a service.

The manual half of the hybrid registry — renewal dates + prices are not API-exposed, so the
operator declares them. Upserts the `subscriptions` row (ON CONFLICT service_id+plan).

    python scripts/declare_subscription.py --provider deepl --price 49 --currency USD \
        --cycle monthly --renews-on 2026-08-01 --account-email ob@ocoron.com
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import registry_db  # noqa: E402


def declare(
    provider: str,
    plan: str = "default",
    price: float | None = None,
    currency: str | None = None,
    cycle: str | None = None,
    renews_on: str | None = None,
    account_email: str | None = None,
) -> None:
    conn = registry_db.connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM services WHERE provider=%s", (provider,))
            row = cur.fetchone()
            if not row:
                raise SystemExit(f"unknown provider '{provider}' — run registry_sync.py first")
            cur.execute(
                """INSERT INTO subscriptions
                     (service_id, plan, price, currency, billing_cycle, renews_on, account_email)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (service_id, plan) DO UPDATE SET price=EXCLUDED.price,
                     currency=EXCLUDED.currency, billing_cycle=EXCLUDED.billing_cycle,
                     renews_on=EXCLUDED.renews_on, account_email=EXCLUDED.account_email""",
                (row[0], plan, price, currency, cycle, renews_on, account_email),
            )
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provider", required=True)
    ap.add_argument("--plan", default="default")
    ap.add_argument("--price", type=float)
    ap.add_argument("--currency")
    ap.add_argument("--cycle")
    ap.add_argument("--renews-on")
    ap.add_argument("--account-email")
    a = ap.parse_args()
    declare(a.provider, a.plan, a.price, a.currency, a.cycle, a.renews_on, a.account_email)
    print(f"declared subscription for {a.provider} (plan={a.plan})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
