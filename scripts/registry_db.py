#!/usr/bin/env python3
# AFTER-EDIT: scripts/registry_sync.py db/services_registry_schema.sql
"""Thin synchronous Postgres connector for the external-services registry.

db-pool was rejected at plan-review: it requires DB_PASSWORD (hard-fails without it) and offers
no DSN / peer-auth path, and a ThreadedConnectionPool is overkill for one sequential cron.
This is the lean replacement — a plain psycopg2 connection over SERVICES_REGISTRY_DSN
(default: the local peer-auth unix-socket DSN, passwordless) + a small execute-with-retry.
"""

from __future__ import annotations

import os
import time

import psycopg2

DEFAULT_DSN = "postgresql:///fabrik_services"


def dsn() -> str:
    return os.getenv("SERVICES_REGISTRY_DSN", DEFAULT_DSN)


def connect():
    """Open a psycopg2 connection to the registry DB (peer-auth socket by default)."""
    return psycopg2.connect(dsn())


def execute_with_retry(cur, query, params=None, retries=3):
    """Run a query, retrying on a transient OperationalError with linear backoff."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            cur.execute(query, params)
            return cur
        except psycopg2.OperationalError as exc:
            last = exc
            time.sleep(0.5 * (attempt + 1))
    raise last  # type: ignore[misc]
