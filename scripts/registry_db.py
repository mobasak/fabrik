#!/usr/bin/env python3
# AFTER-EDIT: scripts/registry_sync.py db/services_registry_schema.sql
"""Thin synchronous Postgres connector for the external-services registry.

db-pool was rejected at plan-review: it requires DB_PASSWORD (hard-fails without it) and offers
no DSN / peer-auth path, and a ThreadedConnectionPool is overkill for one sequential cron.
This is the lean replacement — a plain psycopg2 connection over SERVICES_REGISTRY_DSN
(default: the local peer-auth unix-socket DSN, passwordless). The whole sync is one short
transaction; a lost-connection retry would need a fresh connect() (not a same-cursor re-execute),
so it is NOT provided here — the caller simply re-runs the (idempotent) sync on the next cron tick.
"""

from __future__ import annotations

import os

import psycopg2

DEFAULT_DSN = "postgresql:///fabrik_services"


def dsn() -> str:
    return os.getenv("SERVICES_REGISTRY_DSN", DEFAULT_DSN)


def connect():
    """Open a psycopg2 connection to the registry DB (peer-auth socket by default)."""
    return psycopg2.connect(dsn())
